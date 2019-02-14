#include <cstdint>
#include <cstdlib>
#include <vector>
#include <limits>
#include <stdexcept>
#include <array>
#include "my_queue.h"

typedef double mu_type;
typedef uint16_t coord_type;

const size_t ndim = 3;

namespace
{
template <typename T, size_t K>
size_t inline calculate_position(std::array<T, K> coordinate, std::array<size_t, K> dimension_size)
{
  size_t pos = 0;
  for (size_t i = 0; i < K; i++)
  {
    pos += coordinate[i] * dimension_size[i];
  }
  return pos;
}
template <typename T, size_t K>
bool inline outside_bounds(std::array<T, K> coordinate, std::array<T, K> lower_bound, std::array<T, K> upper_bound)
{
  for (size_t i = 0; i < K; i++)
  {
    if ((lower_bound[i] < coordinate[i]) || (upper_bound[i] >= coordinate[i]))
      return true;
  }
  return false;
}
} // namespace

namespace MSO
{
template <typename T>
/* K is number of dimensions */
class MSO
{
private:
  typedef std::array<coord_type, ndim> Point;

  std::vector<int8_t> neighbourhood;
  std::vector<mu_type> distances;
  std::vector<mu_type> mu_array;
  std::array<coord_type, ndim> size;
  std::array<coord_type, ndim> lower_bound;
  std::array<coord_type, ndim> upper_bound;
  T *components;
  T background_component = 1;

public:
  MSO()
  {
    this->components = nullptr;
    this->size = {0};
  };

  void erase_data()
  {
    /* clean pointers, do not free the memory */
    this->components = nullptr;
    this->size.fill(0);
  }

  inline size_t get_length() const
  {
    size_t res = 1;
    for (size_t i = 0; i < ndim; i++)
      res *= this->size[i];
    return res;
  }

  inline std::array<size_t, ndim> dimension_size() const
  {
    std::array<size_t, ndim> res;
    res[ndim-1] = 1;
    for (size_t i = ndim - 1; i > 0; i--)
    {
      res[i - 1] = res[i] * this->size[i];
    }
    return res;
  }

  template <typename W>
  void set_data(T *components, W size, T background_component = 1)
  {
    this->components = components;
    for (size_t i = 0; i < ndim; i++)
    {
      this->size[i] = size[i];
      this->upper_bound[i] = size[i];
      this->lower_bound[i] = 0;
    }
    this->background_component = background_component;
    if (this->get_length() != this->mu_array.size())
      this->mu_array.clear();
  }

  template <typename W>
  void set_bounding_box(W lower_bound, W upper_bound)
  {
    for (size_t i = 0; i < ndim; i++)
    {
      this->lower_bound[i] = lower_bound[i];
      this->upper_bound[i] = upper_bound[i];
    }
  }

  void set_mu_copy(const std::vector<mu_type> &mu)
  {
    if (mu.size() != this->get_length())
      throw std::length_error("Size of mu array need to be equal to size of components (z_size * y_size * x_size)");
    this->mu_array = mu;
  }
  void set_mu_copy(mu_type *mu, size_t length)
  {
    if (length != this->get_length())
      throw std::length_error("Size of mu array need to be equal to size of components (z_size * y_size * x_size)");
    this->mu_array = std::vector<mu_type>(mu, mu + length);
  }

  void set_mu_swap(std::vector<mu_type> &mu)
  {
    if (mu.size() != this->get_length())
      throw std::length_error("Size of mu array need to be equal to size of components (z_size * y_size * x_size)");
    this->mu_array.swap(mu);
  }

  void set_neighbourhood(std::vector<int8_t> neighbourhood, std::vector<mu_type> distances)
  {
    if (neighbourhood.size() != ndim * distances.size())
    {
      throw std::length_error("Size of neighbouthood need to be 3* Size of distances");
    }
    this->neighbourhood = neighbourhood;
    this->distances = distances;
  }

  void set_neighbourhood(int8_t *neighbourhood, mu_type *distances, size_t neigh_size)
  {
    this->neighbourhood = std::vector<int8_t>(neighbourhood, neighbourhood + 3 * neigh_size);
    this->distances = std::vector<double>(distances, distances + neigh_size);
  }

  void compute_FDT(std::vector<mu_type> &array) const
  {
    if (this->get_length() == 0)
      throw std::runtime_error("call FDT calculation befor set coordinates data");
    if (this->mu_array.size() == 0)
      throw std::runtime_error("call FDT calculation befor set mu array");

    const std::array<size_t, ndim> dimension_size = this->dimension_size();
    Point coord, coord2;
    size_t position, neigh_position;
    my_queue<Point> queue;
    double val, mu_value, fdt_value;
    std::vector<bool> visited_array(this->get_length(), false);
    for (coord[0] = this->lower_bound[0]; coord[0] < this->upper_bound[0]; coord[0]++)
    {
      for (coord[1] = this->lower_bound[1]; coord[1] < this->upper_bound[1]; coord[1]++)
      {
        for (coord[2] = this->lower_bound[2]; coord[2] < this->upper_bound[2]; coord[2]++)
        {
          position = calculate_position(coord, dimension_size);
          array[position] = std::numeric_limits<mu_type>::infinity();
          if (components[position] == this->background_component)
          {
            for (size_t i = 0; i < 3 * this->distances.size(); i += 3)
            {
              for (size_t j = 0; j < ndim; j++)
                coord2[j] = coord[j] + this->neighbourhood[i + j];
              if (outside_bounds(coord2, lower_bound, upper_bound)){
                // continue;
                queue.push(coord);
                break;
              }
              if (components[calculate_position(coord2, dimension_size)] == 0)
              {
                queue.push(coord);
                break;
              }
            }
          }
        }
      }
    }
    std::cout << std::endl << "Queue size " << queue.get_size() << std::endl; 
    size_t count = 0;
    while (!queue.empty())
    {
      count += 1;
      coord = queue.front();
      queue.pop();
      position = calculate_position(coord, dimension_size);
      mu_value = this->mu_array[position];
      fdt_value = array[position];
      for (size_t i = 0; i < this->distances.size(); i++)
      {
        for (size_t j = 0; j < ndim; j++)
          coord2[j] = coord[j] + this->neighbourhood[i + j];
        if (outside_bounds(coord2, lower_bound, upper_bound))
          continue;
        neigh_position = calculate_position(coord2, dimension_size);
        if (components[neigh_position] != 0)
          continue;
        val = (this->mu_array[neigh_position] + mu_value) * distances[i] / 2;
        if (array[neigh_position] > val + fdt_value)
        {
          array[neigh_position] = val + fdt_value;
          if (!visited_array[neigh_position])
          {
            visited_array[neigh_position] = true;
            queue.push(coord2);
          }
        }
      }
      visited_array[position] = false;
    }
    std::cout << "Count " << count << std::endl;
  };

  void set_background_component(T val) { this->background_component = val; };
};

void inline shrink(mu_type &val)
{
  if (val > 1)
    val = 1;
  else if (val < 0)
    val = 0;
}

template <typename T>
std::vector<mu_type> calculate_mu_array(T *array, size_t length, T lower_bound,
                                        T upper_bound)
{
  std::vector<mu_type> result(length, 0);
  mu_type mu;
  for (size_t i = 0; i < length; i++)
  {
    mu = (mu_type)(array[i] - lower_bound) / (upper_bound - lower_bound);
    shrink(mu);
    result[i] = mu;
  }
  return result;
}

template <typename T>
std::vector<mu_type> calculate_reflection_mu_array(T *array, size_t length, T lower_bound,
                                                   T upper_bound)
{
  std::vector<mu_type> result(length, 0);
  mu_type mu;
  for (size_t i = 0; i < length; i++)
  {
    mu = (mu_type)(array[i] - lower_bound) / (upper_bound - lower_bound);
    shrink(mu);
    if (mu < 0.5)
      mu = 1 - mu;
    result[i] = mu;
  }
  return result;
}
template <typename T>
std::vector<mu_type> calculate_two_object_mu(T *array, size_t length, T lower_bound,
                                             T upper_bound, T lower_mid_bound,
                                             T upper_mid_bound)
{
  std::vector<mu_type> result(length, 0);
  mu_type mu;
  T pixel_val;
  for (size_t i = 0; i < length; i++)
  {
    pixel_val = array[i];
    mu = (mu_type)(pixel_val - lower_bound) / (upper_bound - lower_bound);
    if (((lower_bound - lower_mid_bound) > 0) &&
        (pixel_val >= lower_mid_bound) && (pixel_val <= lower_bound))
      mu = (mu_type)(pixel_val - lower_mid_bound) / (lower_bound - lower_mid_bound);
    else if (((upper_bound - lower_bound) > 0) && (lower_bound < pixel_val) &&
             (pixel_val <= upper_bound))
      mu = (mu_type)(upper_bound - pixel_val) / (upper_bound - lower_bound);
    shrink(mu);
    result[i] = mu;
  }
  return result;
}

template <typename T>
std::vector<mu_type> calculate_mu_array_masked(T *array, size_t length, T lower_bound,
                                               T upper_bound, uint8_t *mask)
{
  std::vector<mu_type> result(length, 0);
  mu_type mu;
  for (size_t i = 0; i < length; i++)
  {
    if (mask[i] == 0)
      continue;
    mu = (mu_type)(array[i] - lower_bound) / (upper_bound - lower_bound);
    shrink(mu);
    result[i] = mu;
  }
  return result;
}

template <typename T>
std::vector<mu_type> calculate_reflection_mu_array_masked(T *array, size_t length,
                                                          T lower_bound, T upper_bound,
                                                          uint8_t *mask)
{
  std::vector<mu_type> result(length, 0);
  mu_type mu;
  for (size_t i = 0; i < length; i++)
  {
    if (mask[i] == 0)
      continue;
    mu = (mu_type)(array[i] - lower_bound) / (upper_bound - lower_bound);
    shrink(mu);
    if (mu < 0.5)
      mu = 1 - mu;
    result[i] = mu;
  }
  return result;
}
template <typename T>
std::vector<mu_type> calculate_two_object_mu_masked(T *array, size_t length, T lower_bound,
                                                    T upper_bound, T lower_mid_bound,
                                                    T upper_mid_bound, uint8_t *mask)
{
  std::vector<mu_type> result(length, 0);
  mu_type mu;
  T pixel_val;
  for (size_t i = 0; i < length; i++)
  {
    if (mask[i] == 0)
      continue;
    pixel_val = array[i];
    mu = (mu_type)(pixel_val - lower_bound) / (upper_bound - lower_bound);
    if (((lower_bound - lower_mid_bound) > 0) &&
        (pixel_val >= lower_mid_bound) && (pixel_val <= lower_bound))
      mu = (mu_type)(pixel_val - lower_mid_bound) / (lower_bound - lower_mid_bound);
    else if (((upper_bound - lower_bound) > 0) && (lower_bound < pixel_val) &&
             (pixel_val <= upper_bound))
      mu = (mu_type)(upper_bound - pixel_val) / (upper_bound - lower_bound);
    shrink(mu);
    result[i] = mu;
  }
  return result;
}
} // namespace MSO
